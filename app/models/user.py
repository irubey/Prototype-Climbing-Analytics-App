"""
User model for Send Sage application.

This module defines the core User model with functionality for:
- Authentication and authorization
- Subscription and payment management
- External service integrations
- Usage tracking and rate limiting
- Relationship management with other models
"""

# Standard library imports
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import uuid

# Third-party imports
from sqlalchemy import (
    String,
    Text,
    ForeignKey,
    DateTime,
    Integer,
    Enum as SQLEnum,
    func,
    Boolean
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Application imports
from app.db.base_class import Base

from app.models.enums import UserTier, PaymentStatus

class User(Base):
    """Core user model for authentication and profile data."""
    
    __tablename__ = "users"
    __table_args__ = {"comment": "Core user model for authentication and profile data"}
    
    # Core Authentication
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Payment & Subscription
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(255))
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(255))
    tier: Mapped[UserTier] = mapped_column(SQLEnum(UserTier), default=UserTier.FREE)
    payment_status: Mapped[PaymentStatus] = mapped_column(SQLEnum(PaymentStatus), default=PaymentStatus.INACTIVE)
    last_payment_check: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    stripe_webhook_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Usage Tracking
    daily_message_count: Mapped[int] = mapped_column(Integer, default=0)
    last_message_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Mountain Project Integration
    mountain_project_url: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True)
    mtn_project_last_sync: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # 8a.nu Integration
    eight_a_nu_url: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True)
    eight_a_last_sync: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Relationships
    climber_context: Mapped[Optional["ClimberContext"]] = relationship(
        "ClimberContext", back_populates="user", uselist=False
    )
    uploads: Mapped[List["UserUpload"]] = relationship(
        "UserUpload", back_populates="user"
    )
    user_ticks: Mapped[List["UserTicks"]] = relationship(
        "UserTicks", back_populates="user"
    )
    performance_pyramids: Mapped[List["PerformancePyramid"]] = relationship(
        "PerformancePyramid", back_populates="user"
    )
    chat_histories: Mapped[List["ChatHistory"]] = relationship(
        "ChatHistory", back_populates="user"
    )

    def update_last_login(self) -> None:
        """Update the user's last login timestamp."""
        self.last_login = datetime.now(timezone.utc)

    def update_message_count(self) -> None:
        """Update the user's daily message count.
        
        Resets the counter if it's a new day, otherwise increments the existing count.
        """
        today = datetime.now(timezone.utc).date()
        if self.last_message_date and self.last_message_date.date() == today:
            self.daily_message_count += 1
        else:
            self.daily_message_count = 1
            self.last_message_date = datetime.now(timezone.utc)

    def can_send_message(self, max_daily_messages: int) -> bool:
        """Check if user can send more messages today.
        
        Args:
            max_daily_messages: Maximum number of messages allowed per day
            
        Returns:
            bool: True if user can send more messages, False otherwise
        """
        today = datetime.now(timezone.utc).date()
        if not self.last_message_date or self.last_message_date.date() != today:
            return True
        return self.daily_message_count < max_daily_messages

    @property
    def is_paid(self) -> bool:
        """Check if user has an active paid subscription."""
        return self.payment_status == PaymentStatus.ACTIVE

    @property
    def full_name(self) -> str:
        """Get user's display name."""
        return self.username

    def __str__(self) -> str:
        """String representation of the User model."""
        return f"<User {self.username}>"