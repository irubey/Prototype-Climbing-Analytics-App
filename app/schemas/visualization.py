"""
Visualization and analytics schemas.

This module defines Pydantic models for:
- Climbing tick visualization
- Performance analytics
- Progress tracking
- Location analysis
"""

from datetime import date as DateType
from typing import Dict, List, Optional, Union, Any
from pydantic import BaseModel, Field, UUID4, HttpUrl, model_validator
import math

from app.models.enums import (
    ClimbingDiscipline,
    CruxAngle,
    CruxEnergyType,
    LogbookType
)

class TickData(BaseModel):
    """Schema for individual tick visualization data."""
    route_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Name of the route"
    )
    route_grade: str = Field(
        ...,
        max_length=10,
        description="Grade of the route"
    )
    binned_grade: Optional[str] = Field(
        None,
        max_length=10,
        description="Standardized grade bin"
    )
    binned_code: Optional[int] = Field(
        None,
        ge=0,
        le=200,
        description="Numeric grade code"
    )
    tick_date: DateType = Field(
        ...,
        description="Date of the tick"
    )
    location: str = Field(
        ...,
        max_length=200,
        description="Location of the route"
    )
    discipline: Optional[Union[ClimbingDiscipline, str]] = Field(
        ...,
        description="Climbing discipline"
    )
    send_bool: bool = Field(
        ...,
        description="Whether the route was sent"
    )
    route_url: Optional[Union[HttpUrl, str]] = Field(
        None,
        description="URL of the route"
    )
    route_quality: Optional[float] = Field(
        None,
        ge=0,
        le=5,
        description="Route quality rating"
    )
    logbook_type: Optional[Union[LogbookType, str]] = Field(
        None,
        description="Source of the tick data"
    )
    lead_style: Optional[str] = Field(
        None,
        max_length=50,
        description="Style of lead (e.g., flash, onsight)"
    )


    @model_validator(mode="after")
    def validate_tick_data(self) -> "TickData":
        """Validate tick data."""
        if self.tick_date and self.tick_date > DateType.today():
            raise ValueError("Tick date cannot be in the future")
            
        # Convert NaN route_quality to None
        if self.route_quality is not None and (isinstance(self.route_quality, float) and math.isnan(self.route_quality)):
            self.route_quality = None
            
        return self

class DashboardBaseMetrics(BaseModel):
    """Schema for basic dashboard visualization metrics."""
    recent_ticks: Optional[List[TickData]] = Field(
        [],
        max_length=50,
        description="Recent climbing ticks"
    )
    discipline_stats: Dict[str, int] = Field(
        ...,
        description="Distribution of climbs by discipline"
    )
    grade_distribution: Dict[str, int] = Field(
        ...,
        description="Distribution of climbs by grade"
    )
    total_climbs: int = Field(
        ...,
        ge=0,
        description="Total number of climbs"
    )

    @model_validator(mode="after")
    def validate_metrics(self) -> "DashboardBaseMetrics":
        """Validate metric relationships."""
        # Skip validation if we have no data
        if not self.discipline_stats:
            return self
            
        total = sum(self.discipline_stats.values())
        if total != self.total_climbs:
            raise ValueError("Discipline stats total does not match total climbs")
        return self

class HardSend(BaseModel):
    """Schema for significant send achievements."""
    route_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Name of the route"
    )
    route_grade: str = Field(
        ...,
        max_length=10,
        description="Grade of the route"
    )
    location: str = Field(
        ...,
        max_length=200,
        description="Location of the route"
    )
    send_date: str = Field(
        ...,
        pattern="^\d{4}-\d{2}-\d{2}$",
        description="Date of the send"
    )
    discipline: str = Field(
        ...,
        max_length=50,
        description="Climbing discipline"
    )
    route_url: Optional[str] = Field(
        None,
        max_length=500,
        description="URL of the route"
    )
    lead_style: Optional[str] = Field(
        None,
        max_length=50,
        description="Style of lead"
    )



class DashboardPerformanceMetrics(BaseModel):
    """Schema for performance-focused dashboard metrics."""
    highest_grades: Optional[Dict[str, str]] = Field(
        {},
        description="Highest grades achieved by discipline"
    )
    latest_hard_sends: Optional[List[HardSend]] = Field(
        [],
        max_length=10,
        description="Recent hard sends"
    )


class DetailedPyramidEntry(BaseModel):
    """Schema for detailed pyramid data entry."""
    route_name: str
    tick_date: DateType
    route_grade: str
    binned_grade: Optional[str] = None
    binned_code: Optional[int] = None
    length: Optional[int] = None
    pitches: Optional[int] = None
    location: Optional[str] = None
    location_raw: Optional[str] = None
    lead_style: Optional[str] = None
    cur_max_sport: Optional[int] = None
    cur_max_trad: Optional[int] = None
    cur_max_boulder: Optional[int] = None
    cur_max_tr: Optional[int] = None
    cur_max_alpine: Optional[int] = None
    cur_max_winter_ice: Optional[int] = None
    cur_max_aid: Optional[int] = None
    cur_max_mixed: Optional[int] = None
    difficulty_category: Optional[str] = None
    discipline: Optional[str] = None
    send_bool: bool
    length_category: Optional[str] = None
    season_category: Optional[str] = None
    route_url: Optional[str] = None
    notes: Optional[str] = None
    route_quality: Optional[float] = None
    user_quality: Optional[float] = None
    logbook_type: Optional[str] = None
    tags: List[str] = []
    send_date: Optional[DateType] = None
    crux_angle: Optional[str] = None
    crux_energy: Optional[str] = None
    num_attempts: Optional[int] = None
    days_attempts: Optional[int] = None
    num_sends: Optional[int] = None
    description: Optional[str] = None

class PerformancePyramidData(BaseModel):
    """Schema for grade pyramid visualization data."""
    discipline: str = Field(
        ...,
        description="Climbing discipline"
    )
    grade_counts: Dict[str, int] = Field(
        ...,
        description="Number of sends at each grade"
    )
    total_sends: int = Field(
        ...,
        ge=0,
        description="Total number of sends"
    )
    detailed_data: List[DetailedPyramidEntry] = Field(
        ...,
        description="Detailed tick data with performance metrics"
    )

    @model_validator(mode="after")
    def validate_counts(self) -> "PerformancePyramidData":
        """Validate grade count totals."""
        # Skip validation if there's no data
        if not self.grade_counts:
            return self
            
        if sum(self.grade_counts.values()) != self.total_sends:
            raise ValueError("Grade counts sum does not match total sends")
        return self

class BaseVolumeData(BaseModel):
    """Schema for climbing volume analysis data."""
    ticks_data: List[Dict[str, Any]] = Field(
        [],
        description="All tick data for volume analysis"
    )

class ProgressionData(BaseModel):
    """Schema for climbing progression analysis data."""
    progression_by_discipline: Dict[str, List[Dict[str, Union[DateType, str]]]] = Field(
        {},
        description="Progression data by discipline"
    )


class LocationAnalysis(BaseModel):
    """Schema for climbing location analysis data."""
    location_distribution: Dict[str, Dict[str, Union[int, List[str]]]] = Field(
        {},
        description="Distribution of climbs by location"
    )
    seasonal_patterns: Dict[str, int] = Field(
        {},
        description="Distribution of climbs by season"
    )


    @model_validator(mode="after")
    def validate_seasonal_totals(self) -> "LocationAnalysis":
        """Validate seasonal distribution totals."""
        # Skip validation if there's no data
        if not self.location_distribution or not self.seasonal_patterns:
            return self
            
        location_total = sum(d.get("count", 0) for d in self.location_distribution.values())
        seasonal_total = sum(self.seasonal_patterns.values())
        if location_total != seasonal_total:
            raise ValueError("Location and seasonal totals do not match")
        return self

class PerformanceCharacteristics(BaseModel):
    """Schema for climbing performance characteristics data."""
    crux_types: Dict[str, int] = Field(
        {},
        description="Distribution of climbs by crux type"
    )
    angle_distribution: Dict[str, int] = Field(
        {},
        description="Distribution of climbs by angle"
    )
    energy_distribution: Dict[str, int] = Field(
        {},
        description="Distribution of climbs by energy type"
    )
    attempts_analysis: Dict[str, Union[float, int]] = Field(
        {},
        description="Analysis of climbing attempts"
    )


    @model_validator(mode="after")
    def validate_distributions(self) -> "PerformanceCharacteristics":
        """Validate distribution totals."""
        # Skip validation if there's no data
        if not self.angle_distribution or not self.energy_distribution:
            return self
            
        angle_total = sum(self.angle_distribution.values())
        energy_total = sum(self.energy_distribution.values())
        if angle_total != energy_total:
            raise ValueError("Angle and energy distributions have different totals") 
        
# New models for get_overview_analytics
class OverviewTick(BaseModel):
    """Schema for tick data in overview analytics."""
    route_name: str = Field(..., description="Name of the route")
    tick_date: DateType = Field(..., description="Date of the tick")
    route_grade: str = Field(..., description="Grade of the route")
    binned_code: Optional[int] = Field(None, description="Numeric grade code")
    location: str = Field(..., description="Location of the route")
    lead_style: Optional[str] = Field(None, description="Style of lead (e.g., flash, onsight)")
    difficulty_category: Optional[str] = Field(None, description="Difficulty category relative to max")
    discipline: Optional[ClimbingDiscipline] = Field(None, description="Climbing discipline")
    notes: Optional[str] = Field(None, description="User notes about the tick")
    tags: List[str] = Field(default_factory=list, description="List of tag names associated with the tick")
    num_attempts: Optional[int] = Field(None, ge=0, description="Number of attempts from performance pyramid")
    days_attempts: Optional[int] = Field(None, ge=0, description="Number of days spent attempting from performance pyramid")

class FavoriteLocation(BaseModel):
    """Schema for favorite location data."""
    location: str = Field(..., description="Name of the location")
    pitch_sum: int = Field(..., ge=0, description="Total pitch count at this location")

class UniqueLocations(BaseModel):
    """Schema for unique locations data."""
    num_unique_locations: int = Field(..., ge=0, description="Number of unique locations")
    num_unique_states: int = Field(..., ge=0, description="Number of unique states extracted from locations")

class BaseMetrics(BaseModel):
    """Schema for base metrics in overview analytics."""
    favorite_locations: List[FavoriteLocation] = Field(..., description="Top 3 locations with pitch counts")
    discipline_distribution: Dict[str, int] = Field(..., description="Distribution of climbs by discipline")
    total_pitches: int = Field(..., ge=0, description="Total number of pitches climbed")
    unique_locations: UniqueLocations = Field(..., description="Count of unique locations and states")
    total_days_outside: int = Field(..., ge=0, description="Total number of unique days outside")
    first_day_recorded: Optional[DateType] = Field(None, description="Earliest recorded tick date")

class PerformanceMetrics(BaseModel):
    """Schema for performance metrics in overview analytics."""
    recent_hard_sends: List[OverviewTick] = Field(..., description="Recent hard sends within time range")
    best_performances: Dict[str, List[OverviewTick]] = Field(..., description="Best performances by discipline")
    send_rate: float = Field(..., ge=0, le=100, description="Percentage of sends")
    performance_attempts: int = Field(..., ge=0, description="Total pitches on projects")

class OverviewAnalytics(BaseModel):
    """Schema for overview analytics response."""
    base_metrics: BaseMetrics = Field(..., description="Base climbing metrics")
    performance_metrics: PerformanceMetrics = Field(..., description="Performance-related metrics")