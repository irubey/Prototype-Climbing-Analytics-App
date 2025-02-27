"""
User profile and climber summary schemas.

This module defines Pydantic models for user profiles and climbing-specific data,
including comprehensive validation and documentation for all fields.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, HttpUrl, Field, UUID4, field_validator, model_validator, ConfigDict
from app.models.enums import (
    ClimbingDiscipline,
    CruxAngle,
    CruxEnergyType,
    HoldType,
    UserTier,
    PaymentStatus,
    SessionLength, 
    SleepScore, 
    NutritionScore
)

from app.schemas.auth import UserBase

class UserCreate(UserBase):
    """
    Schema for creating a new user.
    """
    pass

class UserProfile(UserBase):
    """
    Full user profile with all user data and metadata.
    
    This schema extends UserBase to include all user-related data,
    including subscription status, external service connections,
    and usage metrics.
    """
    id: UUID4 = Field(..., description="Unique user identifier")
    tier: UserTier = Field(..., description="User subscription tier")
    payment_status: PaymentStatus = Field(..., description="Payment status")
    stripe_customer_id: Optional[str] = Field(None, description="Stripe customer ID")
    stripe_subscription_id: Optional[str] = Field(None, description="Stripe subscription ID")
    stripe_webhook_verified: bool = Field(False, description="Whether Stripe webhook is verified")
    mountain_project_url: Optional[HttpUrl] = Field(
        None,
        description="Mountain Project profile URL",
        examples=["https://www.mountainproject.com/user/12345/john-doe"]
    )
    eight_a_nu_url: Optional[HttpUrl] = Field(
        None,
        description="8a.nu profile URL",
        examples=["https://www.8a.nu/user/12345"]
    )
    created_at: datetime = Field(..., description="Account creation timestamp")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    is_active: bool = Field(..., description="Whether user account is active")
    daily_message_count: int = Field(0, ge=0, description="Number of messages sent today")
    last_message_date: Optional[datetime] = Field(None, description="Date of last message sent")
    mountain_project_last_sync: Optional[datetime] = Field(None, description="Last Mountain Project data sync")
    eight_a_nu_last_sync: Optional[datetime] = Field(None, description="Last 8a.nu data sync")
    last_payment_check: Optional[datetime] = Field(None, description="Last payment verification check")
    login_attempts: Optional[int] = Field(0, ge=0, description="Failed login attempts")
    last_failed_login: Optional[datetime] = Field(None, description="Last failed login attempt")
    account_locked_until: Optional[datetime] = Field(None, description="Account lock expiration")
    
    model_config = ConfigDict(from_attributes=True)
    
    @field_validator("mountain_project_url", mode="before")
    @classmethod
    def convert_http_url_to_string(cls, v: Any) -> Optional[str]:
        """Convert HttpUrl to string BEFORE validation."""
        if isinstance(v, str):
            return v
        if isinstance(v, HttpUrl):
            return str(v)
        return v

    @field_validator("eight_a_nu_url", mode="before")
    @classmethod
    def convert_eight_a_nu_url_to_string(cls, v: Any) -> Optional[str]:
        if isinstance(v, str):
            return v
        if isinstance(v, HttpUrl):
            return str(v)
        return v

    @model_validator(mode="after")
    def validate_timestamps(self) -> "UserProfile":
        """Validate timestamp relationships."""
        if (self.last_login and self.created_at and 
            self.last_login < self.created_at):
            raise ValueError("Last login cannot be before account creation")
        if (self.last_message_date and self.created_at and 
            self.last_message_date < self.created_at):
            raise ValueError("Last message cannot be before account creation")
        return self

class UserProfileUpdate(BaseModel):
    """
    Schema for updating user profile with validation.
    
    Only allows updating specific fields with appropriate validation
    for each field.
    """
    email: Optional[EmailStr] = Field(
        None,
        description="Updated email address",
        examples=["user@example.com"]
    )
    username: Optional[str] = Field(
        None,
        min_length=3,
        max_length=50,
        pattern="^[a-zA-Z0-9_-]+$",
        description="Updated username (3-50 chars, alphanumeric with _ and -)",
        examples=["john_doe", "climbing_pro"]
    )
    mountain_project_url: Optional[HttpUrl] = Field(
        None,
        description="Updated Mountain Project URL",
        examples=["https://www.mountainproject.com/user/12345/john-doe"]
    )
    eight_a_nu_url: Optional[HttpUrl] = Field(
        None,
        description="Updated 8a.nu URL",
        examples=["https://www.8a.nu/user/12345"]
    )

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: Optional[str]) -> Optional[str]:
        """Validate username format if provided."""
        if v is not None and not v.isalnum() and not all(c in "_-" for c in v if not c.isalnum()):
            raise ValueError("Username can only contain letters, numbers, underscores, and hyphens")
        return v

    @field_validator("mountain_project_url", mode="before")
    @classmethod
    def convert_http_url_to_string(cls, v: Any) -> Optional[str]:
        """Convert HttpUrl to string BEFORE validation."""
        if isinstance(v, str):
            return v
        if isinstance(v, HttpUrl):
            return str(v)
        return v

    @field_validator("eight_a_nu_url", mode="before")
    @classmethod
    def convert_eight_a_nu_url_to_string(cls, v: Any) -> Optional[str]:
        if isinstance(v, str):
            return v
        if isinstance(v, HttpUrl):
            return str(v)
        return v

class SubscriptionRequest(BaseModel):
    """
    Schema for subscription requests with validation.
    
    Validates:
    - Desired tier is a valid UserTier enum value
    - Tier is not FREE (cannot subscribe to free tier)
    """
    desired_tier: UserTier = Field(..., description="Desired subscription tier")

    @model_validator(mode='after')
    def validate_tier(self) -> 'SubscriptionRequest':
        """Validate the desired tier."""
        if self.desired_tier == UserTier.FREE:
            raise ValueError("Cannot subscribe to FREE tier")
        return self

class ClimberSummaryBase(BaseModel):
    """
    Base climber summary fields with comprehensive validation.
    
    This schema captures detailed climbing-specific information including:
    - Experience and goals
    - Performance metrics
    - Training context
    - Lifestyle factors
    - Recent activity
    - Style preferences
    """
    # Basic Information
    climbing_goals: Optional[str] = Field(
        None,
        max_length=1000,
        description="User's climbing goals"
    )
    years_climbing: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Years of climbing experience"
    )
    current_training_description: Optional[str] = Field(
        None,
        max_length=2000,
        description="Current training routine"
    )
    interests: Optional[List[str]] = Field(
        None,
        max_length=20,
        description="Climbing interests"
    )
    injury_information: Optional[str] = Field(
        None,
        max_length=2000,
        description="Injury history"
    )
    additional_notes: Optional[str] = Field(
        None,
        max_length=1000,
        description="Additional notes"
    )
    
    # Experience Base Metrics
    total_climbs: Optional[int] = Field(
        None,
        ge=0,
        le=1000000,
        description="Total number of climbs"
    )
    favorite_discipline: Optional[ClimbingDiscipline] = Field(
        None,
        description="Preferred climbing discipline"
    )
    preferred_crag_last_year: Optional[str] = Field(
        None,
        max_length=200,
        description="Most frequented crag"
    )
    
    # Performance Metrics with Grade Validation
    highest_sport_grade_tried: Optional[str] = Field(
        None,
        max_length=10,
        description="Hardest sport grade attempted"
    )
    highest_trad_grade_tried: Optional[str] = Field(
        None,
        max_length=10,
        description="Hardest trad grade attempted"
    )
    highest_boulder_grade_tried: Optional[str] = Field(
        None,
        max_length=10,
        description="Hardest boulder grade attempted"
    )
    highest_grade_sport_sent_clean_on_lead: Optional[str] = Field(
        None,
        max_length=10,
        description="Hardest sport clean send"
    )
    highest_grade_tr_sent_clean: Optional[str] = Field(
        None,
        max_length=10,
        description="Hardest top rope clean send"
    )
    highest_grade_trad_sent_clean_on_lead: Optional[str] = Field(
        None,
        max_length=10,
        description="Hardest trad clean send"
    )
    highest_grade_boulder_sent_clean: Optional[str] = Field(
        None,
        max_length=10,
        description="Hardest boulder clean send"
    )
    onsight_grade_sport: Optional[str] = Field(
        None,
        max_length=10,
        description="Hardest sport onsight"
    )
    onsight_grade_trad: Optional[str] = Field(
        None,
        max_length=10,
        description="Hardest trad onsight"
    )
    flash_grade_boulder: Optional[str] = Field(
        None,
        max_length=10,
        description="Hardest boulder flash"
    )
    grade_pyramid_sport: Optional[Dict[str, int]] = Field(
        None,
        description="Sport climbing pyramid",
        examples=[{"5.10a": 10, "5.10b": 5, "5.10c": 2}]
    )
    grade_pyramid_trad: Optional[Dict[str, int]] = Field(
        None,
        description="Trad climbing pyramid",
        examples=[{"5.9": 15, "5.10a": 8, "5.10b": 3}]
    )
    grade_pyramid_boulder: Optional[Dict[str, int]] = Field(
        None,
        description="Boulder pyramid",
        examples=[{"V3": 20, "V4": 10, "V5": 5}]
    )
    
    # Training Context
    current_training_frequency: Optional[str] = Field(
        None,
        max_length=100,
        description="Training frequency",
        examples=["3-4 times per week"]
    )
    typical_session_length: Optional[SessionLength] = Field(
        None,
        description="Typical session duration"
    )
    typical_session_intensity: Optional[str] = Field(
        None,
        max_length=100,
        description="Typical session intensity",
        examples=["High intensity with long rests"]
    )
    home_equipment: Optional[str] = Field(
        None,
        max_length=500,
        description="Available home training equipment"
    )
    access_to_commercial_gym: Optional[bool] = Field(
        None,
        description="Has gym access"
    )
    supplemental_training: Optional[str] = Field(
        None,
        max_length=500,
        description="Additional training activities"
    )
    training_history: Optional[str] = Field(
        None,
        max_length=1000,
        description="Training background"
    )
    
    # Lifestyle
    physical_limitations: Optional[str] = Field(
        None,
        max_length=500,
        description="Physical constraints"
    )
    sleep_score: Optional[SleepScore] = Field(
        None,
        description="Sleep quality assessment"
    )
    nutrition_score: Optional[NutritionScore] = Field(
        None,
        description="Nutrition quality assessment"
    )
    
    # Recent Activity
    activity_last_30_days: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Climbs in last 30 days"
    )
    current_projects: Optional[List[Dict[str, Any]]] = Field(
        None,
        max_length=10,
        description="Current project routes"
    )
    recent_favorite_routes: Optional[List[Dict[str, Any]]] = Field(
        None,
        max_length=10,
        description="Recent favorite climbs"
    )
    
    # Style Preferences
    favorite_angle: Optional[CruxAngle] = Field(
        None,
        description="Preferred wall angle"
    )
    weakest_angle: Optional[CruxAngle] = Field(
        None,
        description="Most challenging wall angle"
    )
    strongest_angle: Optional[CruxAngle] = Field(
        None,
        description="Best performing wall angle"
    )
    favorite_energy_type: Optional[CruxEnergyType] = Field(
        None,
        description="Preferred climbing style"
    )
    weakest_energy_type: Optional[CruxEnergyType] = Field(
        None,
        description="Most challenging style"
    )
    strongest_energy_type: Optional[CruxEnergyType] = Field(
        None,
        description="Best performing style"
    )
    favorite_hold_types: Optional[List[HoldType]] = Field(
        None,
        max_length=5,
        description="Preferred hold types"
    )
    weakest_hold_types: Optional[List[HoldType]] = Field(
        None,
        max_length=5,
        description="Most challenging holds"
    )
    strongest_hold_types: Optional[List[HoldType]] = Field(
        None,
        max_length=5,
        description="Best performing holds"
    )

    
    @model_validator(mode="after")
    def validate_grade_relationships(self) -> "ClimberSummaryBase":
        """Validate logical relationships between grades."""
        # Validate sport grades
        if (self.highest_grade_sport_sent_clean_on_lead and 
            self.highest_sport_grade_tried and
            self.highest_grade_sport_sent_clean_on_lead > self.highest_sport_grade_tried):
            raise ValueError("Clean send grade cannot be higher than attempted grade")
            
        # Validate trad grades
        if (self.highest_grade_trad_sent_clean_on_lead and 
            self.highest_trad_grade_tried and
            self.highest_grade_trad_sent_clean_on_lead > self.highest_trad_grade_tried):
            raise ValueError("Clean send grade cannot be higher than attempted grade")
            
        # Validate boulder grades
        if (self.highest_grade_boulder_sent_clean and 
            self.highest_boulder_grade_tried and
            self.highest_grade_boulder_sent_clean > self.highest_boulder_grade_tried):
            raise ValueError("Clean send grade cannot be higher than attempted grade")
            
        return self

class ClimberSummaryCreate(ClimberSummaryBase):
    """Schema for creating a new climber summary."""
    pass

class ClimberSummaryUpdate(ClimberSummaryBase):
    """Schema for updating climber summary."""
    pass

class ClimberSummaryResponse(ClimberSummaryBase):
    """Schema for climber summary response with metadata."""
    user_id: UUID4 = Field(..., description="Associated user ID")
    created_at: datetime = Field(..., description="Record creation timestamp")
    current_info_as_of: datetime = Field(..., description="Last update timestamp")


    
    @model_validator(mode="after")
    def validate_timestamps(self) -> "ClimberSummaryResponse":
        """Validate timestamp relationships."""
        if self.current_info_as_of < self.created_at:
            raise ValueError("Last update cannot be before creation") 