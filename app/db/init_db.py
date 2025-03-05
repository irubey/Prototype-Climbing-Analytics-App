"""
Database initialization and cleanup utilities.
"""

from app.db.session import sessionmanager
from app.db.base_class import Base
from app.models.auth import KeyHistory
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func

async def init_db() -> None:
    """
    Initialize database tables and register models.
    This should be called during application startup.
    """
    from app.core.logging import logger
    # Import auth functions only when needed
    from app.core.auth import generate_key_pair, encrypt_private_key
    
    logger.info("Initializing database")
    async with sessionmanager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with sessionmanager.session() as db:
        try:
            result = await db.execute(select(func.count()).select_from(KeyHistory))
            key_count = result.scalar()
            
            if key_count == 0:
                logger.info("Creating initial key pair")
                private_key, public_key, kid = await generate_key_pair()
                encrypted_private_key = await encrypt_private_key(private_key)
                expires_at = datetime.now(timezone.utc) + timedelta(days=365)

                new_key = KeyHistory(
                    kid=kid,
                    private_key=encrypted_private_key,
                    public_key=public_key,
                    created_at=datetime.now(timezone.utc),
                    expires_at=expires_at,
                )
                db.add(new_key)
                await db.commit()
                logger.info("Initial key pair created")
            else:
                recent_key = await db.execute(
                    select(KeyHistory).order_by(KeyHistory.created_at.desc()).limit(1)
                )
                recent_key_record = recent_key.scalar_one()
                logger.info(f"Found {key_count} keys. Most recent: {recent_key_record.kid}")
        except Exception as e:
            await db.rollback()
            logger.error("Error during key initialization", extra={"error": str(e)}, exc_info=True)
            raise
    
    logger.info("Database initialization complete")

async def dispose_db() -> None:
    """
    Clean up database connections.
    This should be called during application shutdown.
    """
    from app.core.logging import logger
    try:
        logger.info("Disposing database connections")
        await sessionmanager.close()
        logger.info("Database connections disposed")
    except Exception as e:
        logger.error("Error during database disposal", extra={"error": str(e)}, exc_info=True)
        raise 