"""
Chat and messaging models for Send Sage application.

This module defines SQLAlchemy models for:
- Chat history and message storage
- User file uploads and management
- Climber context and preferences
"""

# Standard library imports
from datetime import datetime, timezone
from enum import Enum
import uuid
from typing import Optional, List

# Third-party imports
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
    func
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Application imports
from app.db.base_class import EntityBase
from app.models.enums import (
    ClimbingDiscipline,
    CruxAngle,
    CruxEnergyType,
    HoldType,
    SessionLength,
    SleepScore,
    NutritionScore
)


class ChatHistory(EntityBase):
    __tablename__ = "chat_history"
    
    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="user")  # e.g., "user", "assistant", etc.
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )
    custom_context: Mapped[Optional[str]] = mapped_column(Text)
    is_feedback_helpful: Mapped[Optional[bool]] = mapped_column(Boolean)
    feedback_text: Mapped[Optional[str]] = mapped_column(Text)
    
    user: Mapped["User"] = relationship(
        "User",
        back_populates="chat_histories"
    )
    
    
class UserUpload(EntityBase):
    __tablename__ = "user_uploads"
    
    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)  # in bytes
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)  # e.g., 'txt', 'csv'
    content: Mapped[Optional[str]] = mapped_column(Text)  # if you wish to store raw data
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    file_url: Mapped[Optional[str]] = mapped_column(String)
    content_type: Mapped[Optional[str]] = mapped_column(String)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    processing_error: Mapped[Optional[str]] = mapped_column(Text)
    
    user: Mapped["User"] = relationship(
        "User",
        back_populates="uploads"
    )
    
    
class ClimberContext(EntityBase):
    __tablename__ = "climber_context"
    
    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, unique=True)
    
    # Settings - Core Context additions
    climbing_goals: Mapped[Optional[str]] = mapped_column(Text)
    years_climbing: Mapped[Optional[int]] = mapped_column(Integer)
    current_training_description: Mapped[Optional[str]] = mapped_column(Text)
    interests: Mapped[Optional[dict]] = mapped_column(JSON)
    injury_information: Mapped[Optional[str]] = mapped_column(Text)
    additional_notes: Mapped[Optional[str]] = mapped_column(Text)
    
    # Advanced Settings - Experience Base Metrics
    total_climbs: Mapped[Optional[int]] = mapped_column(Integer)
    favorite_discipline: Mapped[Optional[ClimbingDiscipline]] = mapped_column(SQLEnum(ClimbingDiscipline))
    preferred_crag_last_year: Mapped[Optional[str]] = mapped_column(String(255))
    

    # Advanced Settings - Performance Metrics 
    highest_sport_grade_tried: Mapped[Optional[str]] = mapped_column(String(255))
    highest_trad_grade_tried: Mapped[Optional[str]] = mapped_column(String(255))
    highest_boulder_grade_tried: Mapped[Optional[str]] = mapped_column(String(255))
    highest_grade_sport_sent_clean_on_lead: Mapped[Optional[str]] = mapped_column(String(255))
    highest_grade_tr_sent_clean: Mapped[Optional[str]] = mapped_column(String(255))
    highest_grade_trad_sent_clean_on_lead: Mapped[Optional[str]] = mapped_column(String(255))
    highest_grade_boulder_sent_clean: Mapped[Optional[str]] = mapped_column(String(255))
    onsight_grade_sport: Mapped[Optional[str]] = mapped_column(String(255))
    onsight_grade_trad: Mapped[Optional[str]] = mapped_column(String(255))
    flash_grade_boulder: Mapped[Optional[str]] = mapped_column(String(255))
    grade_pyramid_sport: Mapped[Optional[dict]] = mapped_column(JSON)
    grade_pyramid_trad: Mapped[Optional[dict]] = mapped_column(JSON)
    grade_pyramid_boulder: Mapped[Optional[dict]] = mapped_column(JSON)
    
    # Advanced Settings - Training Context modifications
    current_training_frequency: Mapped[Optional[str]] = mapped_column(String(255))  # Renamed from training_frequency
    typical_session_length: Mapped[Optional[SessionLength]] = mapped_column(SQLEnum(SessionLength))
    typical_session_intensity: Mapped[Optional[str]] = mapped_column(String(255))  # New Field
    home_equipment: Mapped[Optional[str]] = mapped_column(Text)  # New Field replacing has_hangboard and has_home_wall
    access_to_commercial_gym: Mapped[bool] = mapped_column(Boolean, default=False)  # Renamed from goes_to_gym
    supplemental_training: Mapped[Optional[str]] = mapped_column(Text)  # New Field
    training_history: Mapped[Optional[str]] = mapped_column(Text)  # New Field
    
    # Advanced Settings - Lifestyle
    physical_limitations: Mapped[Optional[str]] = mapped_column(Text)
    sleep_score: Mapped[Optional[SleepScore]] = mapped_column(SQLEnum(SleepScore))
    nutrition_score: Mapped[Optional[NutritionScore]] = mapped_column(SQLEnum(NutritionScore))
    
    
    # Advanced Settings - Recent Activity 
    activity_last_30_days: Mapped[Optional[int]] = mapped_column(Integer)
    current_projects: Mapped[Optional[dict]] = mapped_column(JSON)
    recent_favorite_routes: Mapped[Optional[dict]] = mapped_column(JSON)
    
    # Advanced Settings - Style Preferences
    favorite_angle: Mapped[Optional[CruxAngle]] = mapped_column(SQLEnum(CruxAngle))
    weakest_angle: Mapped[Optional[CruxAngle]] = mapped_column(SQLEnum(CruxAngle))
    strongest_angle: Mapped[Optional[CruxAngle]] = mapped_column(SQLEnum(CruxAngle))
    favorite_energy_type: Mapped[Optional[CruxEnergyType]] = mapped_column(SQLEnum(CruxEnergyType))
    weakest_energy_type: Mapped[Optional[CruxEnergyType]] = mapped_column(SQLEnum(CruxEnergyType))
    strongest_energy_type: Mapped[Optional[CruxEnergyType]] = mapped_column(SQLEnum(CruxEnergyType))
    favorite_hold_types: Mapped[Optional[HoldType]] = mapped_column(SQLEnum(HoldType))
    weakest_hold_types: Mapped[Optional[HoldType]] = mapped_column(SQLEnum(HoldType))
    strongest_hold_types: Mapped[Optional[HoldType]] = mapped_column(SQLEnum(HoldType))
    

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    current_info_as_of: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(),
        onupdate=func.now()
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="climber_context"
    )

    def __repr__(self) -> str:
        return f"<ClimberContext(id={self.id}, user_id={self.user_id})>"