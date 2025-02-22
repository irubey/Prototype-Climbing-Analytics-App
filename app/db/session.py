"""
Database session management and configuration.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional, Any, Dict
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
    AsyncEngine
)
from sqlalchemy.pool import Pool, NullPool
from fastapi import Request, FastAPI

from app.db.base_class import Base

# --- Helper Function to get settings ---
def _get_settings():
    from app.core import settings  # Import inside the getter function
    return settings

# --- Helper Function to get logger ---
def _get_logger():
    from app.core.logging import logger
    return logger

class DatabaseSessionManager:
    """
    A session manager to handle database connections and session lifecycle.
    Ensures proper initialization and cleanup of database resources.
    """
    _instance: Optional['DatabaseSessionManager'] = None
    _initialized = False

    def __init__(self):
        self._engine: Optional[AsyncEngine] = None
        self._sessionmaker: Optional[async_sessionmaker] = None
        # Counter for monitoring initialization
        self._init_call_count = 0
        self.settings = _get_settings()

    @classmethod
    def get_instance(cls) -> 'DatabaseSessionManager':
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def init(
        self,
        db_url: str,
        *,
        poolclass: Optional[type[Pool]] = None,
        engine_kwargs: Optional[Dict[str, Any]] = None,
        session_kwargs: Optional[Dict[str, Any]] = None,
        force: bool = False
    ) -> None:
        """
        Initialize database engine and session maker.
        """
        logger = _get_logger()
        self._init_call_count += 1
        logger.info(
            "DatabaseSessionManager.init called",
            extra={
                "call_count": self._init_call_count,
                "already_initialized": self._initialized,
                "force": force,
                "is_test_db": 'test' in str(db_url)
            }
        )

        if self._initialized and not force:
            logger.warning("DatabaseSessionManager already initialized. Use force=True to reinitialize.")
            return

        if 'test' not in str(db_url) and self.settings.TESTING:
            logger.error("Attempting to use non-test database in test environment")
            raise ValueError(
                "Attempting to use non-test database in test environment. "
                "Ensure TEST_DB_URL is properly configured."
            )

        # Prepare engine configuration *conditionally*
        default_engine_kwargs = {
            "pool_pre_ping": True,
            "echo": self.settings.ENVIRONMENT == "development"
        }
        # Only add pooling arguments if NOT using NullPool
        if poolclass is None or poolclass is not NullPool:
            default_engine_kwargs.update({
                "pool_size": 5,
                "max_overflow": 10,
                "pool_timeout": 30,
            })
        if poolclass is not None:
            default_engine_kwargs["poolclass"] = poolclass
        if engine_kwargs:
            default_engine_kwargs.update(engine_kwargs)

        logger.debug(
            "Creating engine",
            extra={"engine_kwargs": default_engine_kwargs}
        )

        # Create engine
        self._engine = create_async_engine(
            str(db_url).replace("postgresql://", "postgresql+asyncpg://"),
            **default_engine_kwargs
        )

        # Prepare session configuration
        default_session_kwargs = {
            "class_": AsyncSession,
            "expire_on_commit": False,
            "autocommit": False,
            "autoflush": False
        }
        if session_kwargs:
            default_session_kwargs.update(session_kwargs)

        logger.debug(
            "Creating session maker",
            extra={"session_kwargs": default_session_kwargs}
        )

        # Create session maker
        self._sessionmaker = async_sessionmaker(
            self._engine,
            **default_session_kwargs
        )
        
        self._initialized = True
        logger.info(
            "DatabaseSessionManager initialized",
            extra={"db_url": db_url}
        )

    async def close(self) -> None:
        """Close database connections."""
        logger = _get_logger()
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._sessionmaker = None
            self._initialized = False
            logger.info("Closed all database connections")

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get a database session.
        Session is automatically closed when context exits.
        Commits must be handled explicitly by the caller.
        """
        logger = _get_logger()
        if not self._initialized or self._sessionmaker is None:
            raise RuntimeError(
                "DatabaseSessionManager is not initialized. "
                "Call init() before requesting sessions."
            )

        session: AsyncSession = self._sessionmaker()
        try:
            yield session
        finally:
            await session.close()

    @property
    def engine(self) -> AsyncEngine:
        """Get the current database engine."""
        logger = _get_logger()
        if not self._initialized or self._engine is None:
            raise RuntimeError(
                "DatabaseSessionManager is not initialized. "
                "Call init() before accessing engine."
            )
        return self._engine

    @property
    def initialized(self) -> bool:
        """Check if the session manager is initialized."""
        return self._initialized

# Global session manager instance - NOT initialized by default
sessionmanager = DatabaseSessionManager.get_instance()

async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that yields a database session using the db_manager attached to app state.
    """
    async with request.app.state.db_manager.session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

async def create_all() -> None:
    """Create all database tables asynchronously."""
    async with sessionmanager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def drop_all() -> None:
    """Drop all database tables asynchronously."""
    async with sessionmanager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all) 