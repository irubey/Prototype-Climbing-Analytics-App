"""
Key rotation management for Send Sage application.

This module provides functionality for:
- Automatic key rotation on a schedule
- Key pair generation and storage
- Grace period management
"""

from datetime import datetime, timedelta, timezone
from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import generate_key_pair, encrypt_private_key
from app.core.logging import logger
from app.models.auth import KeyHistory

async def rotate_keys(background_tasks: BackgroundTasks, db: AsyncSession) -> None:
    """
    Background task to handle key rotation.
    Generates new key pair and stores it in the database.
    """
    from app.core.config import settings

    try:
        # Generate new key pair
        private_key, public_key, kid = await generate_key_pair()

        # Encrypt private key
        encrypted_private_key = await encrypt_private_key(private_key)

        # Calculate expiration
        created_at = datetime.now(timezone.utc)
        expires_at = created_at + timedelta(
            days=settings.KEY_ROTATION_INTERVAL_DAYS +
                 settings.KEY_ROTATION_GRACE_PERIOD_DAYS
        )

        # Store in database
        new_key = KeyHistory(
            kid=kid,
            private_key=encrypted_private_key,
            public_key=public_key,
            created_at=created_at,
            expires_at=expires_at
        )
        db.add(new_key)
        await db.commit()

        logger.info(
            "Key rotation completed successfully",
            extra={
                "kid": kid,
                "expires_at": expires_at.isoformat()
            }
        )

        # Schedule next rotation
        background_tasks.add_task(
            schedule_next_rotation,
            db,
            timedelta(days=settings.KEY_ROTATION_INTERVAL_DAYS)
        )

    except Exception as e:
        logger.error(
            "Key rotation failed",
            extra={
                "error": str(e),
                "error_type": type(e).__name__
            }
        )
        # Alert operations team
        await alert_ops_team("Key rotation failed", str(e))

async def schedule_next_rotation(
    db: AsyncSession,
    interval: timedelta
) -> None:
    """Schedule the next key rotation."""
    from app.core.config import settings

    try:
        # Calculate next rotation time
        next_rotation = datetime.now(timezone.utc) + interval

        logger.info(
            "Scheduled next key rotation",
            extra={"next_rotation": next_rotation.isoformat()}
        )

        # Store next rotation time in database or cache
        # This is application specific and depends on your infrastructure

    except Exception as e:
        logger.error(
            "Failed to schedule next key rotation",
            extra={
                "error": str(e),
                "error_type": type(e).__name__
            }
        )

async def alert_ops_team(subject: str, message: str) -> None:
    """Alert operations team about key rotation issues."""
    # This is application specific and depends on your monitoring setup
    logger.error(
        "Key rotation alert",
        extra={
            "subject": subject,
            "message": message
        }
    ) 