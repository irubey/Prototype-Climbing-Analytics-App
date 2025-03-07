"""
Climbing data models for Send Sage application.

This module defines SQLAlchemy models for:
- Climbing routes and ascents
- Performance tracking and analysis
- Grade conversion and binning
- Tagging and categorization
"""

# Core imports
from datetime import datetime, timezone, date
from enum import Enum
from typing import Any, Dict, Optional, ClassVar, Type, List
from uuid import UUID

# SQLAlchemy imports
from sqlalchemy import (
    String,
    Text,
    ForeignKey,
    Float,
    DateTime,
    Enum as SQLEnum,
    func,
    Integer,
    Boolean,
    Date
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, joinedload

# Local imports with tracking
from app.db.base_class import Base
from app.models.enums import (
    ClimbingDiscipline,
    CruxAngle,
    CruxEnergyType,
    HoldType,
    LogbookType
)

class UserTicks(Base):
    """Records of user's climbing attempts and sends."""
    
    __tablename__ = "user_ticks"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    route_name: Mapped[Optional[str]] = mapped_column(String(255))
    tick_date: Mapped[Optional[Date]] = mapped_column(Date, index=True)
    route_grade: Mapped[Optional[str]] = mapped_column(String(255))
    binned_grade: Mapped[Optional[str]] = mapped_column(String(255))
    binned_code: Mapped[Optional[int]] = mapped_column(Integer)
    length: Mapped[Optional[int]] = mapped_column(Integer)
    pitches: Mapped[Optional[int]] = mapped_column(Integer)
    #location: crag, area
    location: Mapped[Optional[str]] = mapped_column(String(255))
    #mountain project full location string
    location_raw: Mapped[Optional[str]] = mapped_column(String(255))
    #redpoint, flash, onsight, etc.
    lead_style: Mapped[Optional[str]] = mapped_column(String(255))
    cur_max_rp_sport: Mapped[Optional[int]] = mapped_column(Integer)
    cur_max_rp_trad: Mapped[Optional[int]] = mapped_column(Integer)
    cur_max_boulder: Mapped[Optional[int]] = mapped_column(Integer)
    #difficulty category relative to cur max
    difficulty_category: Mapped[Optional[str]] = mapped_column(String(255))
    discipline: Mapped[Optional[ClimbingDiscipline]] = mapped_column(SQLEnum(ClimbingDiscipline))
    send_bool: Mapped[Optional[bool]] = mapped_column(Boolean)
    length_category: Mapped[Optional[str]] = mapped_column(String(255))
    season_category: Mapped[Optional[str]] = mapped_column(String(255))
    route_url: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    notes: Mapped[Optional[str]] = mapped_column(Text)
    #consensus quality score
    route_quality: Mapped[Optional[float]] = mapped_column(Float)
    #user quality score
    user_quality: Mapped[Optional[float]] = mapped_column(Float)
    logbook_type: Mapped[Optional[LogbookType]] = mapped_column(SQLEnum(LogbookType))

    # Relationships with type annotations
    user: Mapped["User"] = relationship(
        "User",
        back_populates="user_ticks",
    )
    performance_pyramid: Mapped[List["PerformancePyramid"]] = relationship(
        "PerformancePyramid",
        back_populates="tick",
    )
    tags: Mapped[List["Tag"]] = relationship(
        "Tag",
        secondary="user_ticks_tags",
        back_populates="ticks",
    )

    def __str__(self) -> str:
        return f"<UserTicks {self.route_name} ({self.route_grade})>"
    
    @property
    def performance_pyramid_joined(self):
        """
        Returns the UserTicks instance joined with its corresponding PerformancePyramid data.
        """
        if not self.performance_pyramid:
            return None  # or handle as needed (e.g., empty list/dict)
        
        # Use SQLAlchemy's session to load the joined data
        from sqlalchemy.orm import Session
        from app.db.session import SessionLocal  # Assuming you have a session factory
        
        with SessionLocal() as session:
            result = (
                session.query(UserTicks)
                .options(joinedload(UserTicks.performance_pyramid))
                .filter(UserTicks.id == self.id)
                .one_or_none()
            )
            if result:
                return result.performance_pyramid
            return None
        
class UserTicksTags(Base):
    """Association table for user ticks and tags."""
    
    __tablename__ = "user_ticks_tags"
    
    user_tick_id: Mapped[int] = mapped_column(Integer, ForeignKey("user_ticks.id"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(Integer, ForeignKey("tags.id"), primary_key=True)

class Tag(Base):
    """Tags for categorizing climbs."""
    
    __tablename__ = "tags"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    
    # Relationship with type annotation
    ticks: Mapped[List["UserTicks"]] = relationship(
        "UserTicks",
        secondary="user_ticks_tags",
        back_populates="tags",
    )

class PerformancePyramid(Base):
    """Performance analysis data for climbing routes."""
    
    __tablename__ = "performance_pyramid"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    tick_id: Mapped[int] = mapped_column(Integer, ForeignKey("user_ticks.id"), nullable=False)
    send_date: Mapped[Date] = mapped_column(Date, nullable=False, index=True)
    location: Mapped[Optional[str]] = mapped_column(String(255))
    crux_angle: Mapped[Optional[CruxAngle]] = mapped_column(SQLEnum(CruxAngle))
    crux_energy: Mapped[Optional[CruxEnergyType]] = mapped_column(SQLEnum(CruxEnergyType))
    binned_code: Mapped[int] = mapped_column(Integer, nullable=False)
    num_attempts: Mapped[Optional[int]] = mapped_column(Integer)
    days_attempts: Mapped[Optional[int]] = mapped_column(Integer)
    num_sends: Mapped[Optional[int]] = mapped_column(Integer)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Relationships with type annotations
    user: Mapped["User"] = relationship(
        "User",
        back_populates="performance_pyramids",
    )
    tick: Mapped["UserTicks"] = relationship(
        "UserTicks",
        back_populates="performance_pyramid",
    )

    def __str__(self) -> str:
        return f"<PerformancePyramid {self.id}>"
