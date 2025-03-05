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
from fastapi import Request

from app.db.base_class import Base

# --- Helper Functions ---
def _get_settings():
    from app.core import settings
    return settings

def _get_logger():
    from app.core.logging import logger
    return logger

class DatabaseSessionManager:
    _instance: Optional['DatabaseSessionManager'] = None
    _initialized = False

    def __init__(self):
        self._engine: Optional[AsyncEngine] = None
        self._sessionmaker: Optional[async_sessionmaker] = None
        self._init_call_count = 0
        self.settings = _get_settings()

    @classmethod
    def get_instance(cls) -> 'DatabaseSessionManager':
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
        logger = _get_logger()
        self._init_call_count += 1
        logger.info(
            "DatabaseSessionManager.init called",
            extra={"call_count": self._init_call_count, "force": force}
        )

        if self._initialized and not force:
            logger.warning("DatabaseSessionManager already initialized.")
            return

        if 'test' not in str(db_url) and self.settings.TESTING:
            logger.error("Non-test DB in test environment")
            raise ValueError("Ensure TEST_DB_URL is configured.")

        default_engine_kwargs = {
            "pool_pre_ping": True,
            "echo": self.settings.ENVIRONMENT == "development"
        }
        if poolclass is None or poolclass is not NullPool:
            default_engine_kwargs.update({
                "pool_size": 5,
                "max_overflow": 10,
                "pool_timeout": 30,
            })
        if poolclass:
            default_engine_kwargs["poolclass"] = poolclass
        if engine_kwargs:
            default_engine_kwargs.update(engine_kwargs)

        self._engine = create_async_engine(
            str(db_url).replace("postgresql://", "postgresql+asyncpg://"),
            **default_engine_kwargs
        )

        default_session_kwargs = {
            "class_": AsyncSession,
            "expire_on_commit": False,
            "autocommit": False,
            "autoflush": False
        }
        if session_kwargs:
            default_session_kwargs.update(session_kwargs)

        self._sessionmaker = async_sessionmaker(
            self._engine,
            **default_session_kwargs
        )
        self._initialized = True
        logger.info("DatabaseSessionManager initialized")

    async def close(self) -> None:
        logger = _get_logger()
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._sessionmaker = None
            self._initialized = False
            logger.info("Closed all database connections")

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        if not self._initialized or self._sessionmaker is None:
            raise RuntimeError("DatabaseSessionManager not initialized.")
        session: AsyncSession = self._sessionmaker()
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    @property
    def engine(self) -> AsyncEngine:
        if not self._initialized or self._engine is None:
            raise RuntimeError("DatabaseSessionManager not initialized.")
        return self._engine

    @property
    def initialized(self) -> bool:
        return self._initialized

# Global instance
sessionmanager = DatabaseSessionManager.get_instance()

# Updated get_db to use request.state
async def get_db(request: Request) -> AsyncSession:
    """
    Dependency that retrieves the request-scoped database session.
    """
    if not hasattr(request.state, 'db'):
        raise RuntimeError("Request-scoped session not initialized. Ensure DBSessionMiddleware is added.")
    return request.state.db

async def create_all() -> None:
    async with sessionmanager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def drop_all() -> None:
    async with sessionmanager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all) 