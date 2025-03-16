"""
Authentication models for Send Sage application.

This module defines SQLAlchemy models for:
- Token revocation tracking
- Key rotation history
- JWT signing key management
"""

from datetime import datetime
import uuid
from typing import Optional

from sqlalchemy import String, DateTime, func, LargeBinary, Column, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import EntityBase

class RevokedToken(EntityBase):
    """Model for tracking revoked JWT tokens."""
    __tablename__ = "revoked_tokens"
    __table_args__ = {"comment": "Track revoked JWT tokens to prevent reuse"}

    jti: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False
    )
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    def __repr__(self) -> str:
        return f"<RevokedToken {self.jti}>"

class KeyHistory(EntityBase):
    """Store key rotation history with encrypted private keys."""
    
    __tablename__ = "key_history"
    __table_args__ = {"comment": "Store key rotation history with encrypted private keys"}
    
    kid: Mapped[str] = mapped_column(String(255), nullable=False, index=True, unique=True)
    private_key: Mapped[LargeBinary] = mapped_column(LargeBinary, nullable=False)
    public_key: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    def __str__(self) -> str:
        return f"<KeyHistory {self.id}>" 