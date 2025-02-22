"""
Visualization and analytics schemas.

This module defines Pydantic models for:
- Climbing tick visualization
- Performance analytics
- Progress tracking
- Location analysis
"""

from datetime import date as DateType
from typing import Dict, List, Optional, Union
from pydantic import BaseModel, Field, UUID4, HttpUrl, model_validator

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
        le=100,
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
    discipline: ClimbingDiscipline = Field(
        ...,
        description="Climbing discipline"
    )
    send_bool: bool = Field(
        ...,
        description="Whether the route was sent"
    )
    route_url: Optional[HttpUrl] = Field(
        None,
        description="URL of the route"
    )
    route_quality: Optional[float] = Field(
        None,
        ge=0,
        le=5,
        description="Route quality rating"
    )
    logbook_type: Optional[LogbookType] = Field(
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
        if self.tick_date > DateType.today():
            raise ValueError("Tick date cannot be in the future")
        return self

class DashboardBaseMetrics(BaseModel):
    """Schema for basic dashboard visualization metrics."""
    recent_ticks: List[TickData] = Field(
        ...,
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
    highest_grades: Dict[str, str] = Field(
        ...,
        description="Highest grades achieved by discipline"
    )
    latest_hard_sends: List[HardSend] = Field(
        ...,
        max_length=10,
        description="Recent hard sends"
    )



class PerformancePyramidData(BaseModel):
    """Schema for grade pyramid visualization data."""
    discipline: ClimbingDiscipline = Field(
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


    @model_validator(mode="after")
    def validate_counts(self) -> "PerformancePyramidData":
        """Validate grade count totals."""
        if sum(self.grade_counts.values()) != self.total_sends:
            raise ValueError("Grade counts sum does not match total sends")
        return self

class BaseVolumeData(BaseModel):
    """Schema for climbing volume analysis data."""
    volume_by_difficulty: Dict[str, Dict[str, Union[int, float]]] = Field(
        ...,
        description="Volume metrics by difficulty category"
    )

class ProgressionData(BaseModel):
    """Schema for climbing progression analysis data."""
    progression_by_discipline: Dict[ClimbingDiscipline, List[Dict[str, Union[DateType, str]]]] = Field(
        ...,
        description="Progression data by discipline"
    )


class LocationAnalysis(BaseModel):
    """Schema for climbing location analysis data."""
    location_distribution: Dict[str, Dict[str, Union[int, List[str]]]] = Field(
        ...,
        description="Distribution of climbs by location"
    )
    seasonal_patterns: Dict[str, int] = Field(
        ...,
        description="Distribution of climbs by season"
    )


    @model_validator(mode="after")
    def validate_seasonal_totals(self) -> "LocationAnalysis":
        """Validate seasonal distribution totals."""
        location_total = sum(d.get("count", 0) for d in self.location_distribution.values())
        seasonal_total = sum(self.seasonal_patterns.values())
        if location_total != seasonal_total:
            raise ValueError("Location and seasonal totals do not match")
        return self

class PerformanceCharacteristics(BaseModel):
    """Schema for climbing performance characteristics data."""
    angle_distribution: Dict[CruxAngle, int] = Field(
        ...,
        description="Distribution of climbs by angle"
    )
    energy_distribution: Dict[CruxEnergyType, int] = Field(
        ...,
        description="Distribution of climbs by energy type"
    )
    attempts_analysis: Dict[str, Union[float, int]] = Field(
        ...,
        description="Analysis of climbing attempts"
    )


    @model_validator(mode="after")
    def validate_distributions(self) -> "PerformanceCharacteristics":
        """Validate distribution totals."""
        angle_total = sum(self.angle_distribution.values())
        energy_total = sum(self.energy_distribution.values())
        if angle_total != energy_total:
            raise ValueError("Angle and energy distributions have different totals") 