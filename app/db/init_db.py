"""
Database initialization and cleanup utilities.
"""

from app.db.session import sessionmanager
from app.db.base_class import Base
from app.models.auth import KeyHistory
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from uuid import uuid4

async def init_db() -> None:
    """
    Initialize database tables and register models.
    This should be called during application startup.
    """
    from app.core.logging import logger
    # Import auth functions only when needed
    from app.core.auth import generate_key_pair, encrypt_private_key
    
    try:
        logger.info("Initializing database")
        
        # Create tables
        async with sessionmanager.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
        # --- Key Initialization ---
        async with sessionmanager.session() as db:
            try:
                # Check if KeyHistory is empty
                result = await db.execute(select(KeyHistory))
                existing_key = result.scalar_one_or_none()

                if not existing_key:
                    logger.info("No existing keys found. Creating initial key pair.")
                    private_key, public_key, kid = await generate_key_pair()
                    encrypted_private_key = await encrypt_private_key(private_key)
                    expires_at = datetime.now(timezone.utc) + timedelta(days=365)

                    new_key = KeyHistory(
                        id=kid,
                        private_key=encrypted_private_key,
                        public_key=public_key,
                        created_at=datetime.now(timezone.utc),
                        expires_at=expires_at,
                    )
                    db.add(new_key)
                    await db.commit()
                    logger.info("Initial key pair created and stored.")

                    # Verification: Check if the key exists *after* commit
                    result = await db.execute(select(KeyHistory))
                    verify_key = result.scalar_one_or_none()
                    if verify_key:
                        logger.info(f"Key verification successful. KID: {verify_key.id}")
                    else:
                        logger.error("Key verification FAILED. Key not found after commit.")
                        raise RuntimeError("Key not found after commit")  # Critical error

                else:
                    logger.info("Existing key found. Skipping key initialization.")

            except Exception as e:
                await db.rollback()  # Rollback if any error occurs within the inner transaction
                logger.error(
                    "Error during key initialization",
                    extra={
                        "error": str(e),
                        "error_type": type(e).__name__
                    },
                    exc_info=True
                )
                raise  # Re-raise the exception

        # --- End Key Initialization ---
        
        logger.info("Database initialization complete")
        
    except Exception as e:
        logger.error(
            "Error during database initialization",
            extra={
                "error": str(e),
                "error_type": type(e).__name__
            },
            exc_info=True
        )
        raise

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
        logger.error(
            "Error during database disposal",
            extra={
                "error": str(e),
                "error_type": type(e).__name__
            },
            exc_info=True
        )
        raise 