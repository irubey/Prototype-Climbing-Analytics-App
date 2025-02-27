"""Test configuration settings."""
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import PostgresDsn

class TestSettings(BaseSettings):
    """Test environment settings."""

    # Environment selection
    TEST_ENV: str = "local"  # Options: local, ci, docker

    # Paths
    BASE_DIR: Path = Path(__file__).parent.parent.parent
    TEST_DATA_DIR: Path = Path(__file__).parent / "data" / "fixtures"

    # Database
    TEST_DATABASE_URL: PostgresDsn = "postgresql+asyncpg://postgres:postgres@localhost/test_db"

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

    model_config = SettingsConfigDict(
        env_file=".env.test",
        case_sensitive=True
    )

# Create a global instance
test_settings = TestSettings() 