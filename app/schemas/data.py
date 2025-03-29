"""
Data schemas for climbing logbook and performance tracking.

This module defines Pydantic models for:
- Climbing ticks and performance data
- Grade conversion and binning
- Data import/export
- Tag management
"""

from datetime import date, datetime
from typing import List, Optional, Dict, Any, Set
from pydantic import BaseModel, Field, UUID4, HttpUrl, model_validator

from app.models.enums import (
    ClimbingDiscipline,
    CruxAngle,
    CruxEnergyType,
    LogbookType
)

class BinnedCode(BaseModel):
    """Schema for standardized grade binning."""
    binned_code: int = Field(
        ...,
        ge=0,
        le=300,
        description="Numeric grade code"
    )
    binned_grade: str = Field(
        ...,
        max_length=10,
        description="Standardized grade name"
    )


class PyramidInput(BaseModel):
    """Schema for manual performance pyramid data input."""
    tick_id: int = Field(..., ge=1, description="ID of the associated tick")
    first_sent: date = Field(..., description="Date of first successful send")
    crux_angle: Optional[CruxAngle] = Field(None, description="Angle of the crux")
    crux_energy: Optional[CruxEnergyType] = Field(None, description="Energy type of the crux")
    num_attempts: Optional[int] = Field(
        None,
        ge=1,
        le=1000,
        description="Number of attempts"
    )
    days_attempts: Optional[int] = Field(
        None,
        ge=1,
        le=365,
        description="Days spent attempting"
    )
    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Additional notes or description"
    )
    agg_notes: Optional[str] = Field(
        None,
        max_length=1000,
        description="Aggregated notes from multiple attempts"
    )


    @model_validator(mode="after")
    def validate_attempts(self) -> "PyramidInput":
        """Validate attempt counts."""
        if (self.days_attempts and self.num_attempts and 
            self.days_attempts > self.num_attempts):
            raise ValueError("Days attempting cannot exceed number of attempts")
        return self

class PerformanceData(BaseModel):
    """Schema for detailed performance metrics."""
    first_sent: date = Field(..., description="Date of first successful send")
    crux_angle: Optional[CruxAngle] = Field(None, description="Angle of the crux")
    crux_energy: Optional[CruxEnergyType] = Field(None, description="Energy type of the crux")
    num_attempts: Optional[int] = Field(
        None,
        ge=1,
        le=1000,
        description="Number of attempts"
    )
    days_attempts: Optional[int] = Field(
        None,
        ge=1,
        le=365,
        description="Days spent attempting"
    )
    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Additional notes"
    )
    num_sends: Optional[int] = Field(
        None,
        ge=0,
        le=1000,
        description="Number of successful sends"
    )
    agg_notes: Optional[str] = Field(
        None,
        max_length=1000,
        description="Aggregated notes from multiple attempts"
    )



    @model_validator(mode="after")
    def validate_metrics(self) -> "PerformanceData":
        """Validate performance metrics relationships."""
        if (self.days_attempts and self.num_attempts and 
            self.days_attempts > self.num_attempts):
            raise ValueError("Days attempting cannot exceed number of attempts")
        if (self.num_sends and self.num_attempts and 
            self.num_sends > self.num_attempts):
            raise ValueError("Number of sends cannot exceed number of attempts")
        return self

class TickCreate(BaseModel):
    """Schema for creating a new climbing tick."""
    route_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Name of the route"
    )
    route_grade: str = Field(
        ...,
        max_length=50,
        description="Grade of the route"
    )
    binned_grade: Optional[str] = Field(
        None,
        max_length=50,
        description="Standardized grade bin"
    )
    binned_code: Optional[int] = Field(
        None,
        ge=0,
        le=300,
        description="Numeric grade code"
    )
    tick_date: date = Field(..., description="Date of the tick")
    location: str = Field(
        ...,
        max_length=200,
        description="Location of the route"
    )
    location_raw: Optional[str] = Field(
        None,
        max_length=500,
        description="Raw location string"
    )
    discipline: Optional[ClimbingDiscipline] = Field(None, description="Climbing discipline")
    length: Optional[int] = Field(
        None,
        ge=0,
        le=2000,
        description="Length in meters"
    )
    pitches: Optional[int] = Field(
        None,
        ge=1,
        le=100,
        description="Number of pitches"
    )
    lead_style: Optional[str] = Field(
        None,
        max_length=50,
        description="Style of lead"
    )
    send_bool: bool = Field(..., description="Whether the route was sent")
    route_url: Optional[HttpUrl] = Field(None, description="URL of the route")
    notes: Optional[str] = Field(
        None,
        max_length=1000,
        description="Additional notes"
    )
    route_quality: Optional[float] = Field(
        None,
        ge=0,
        le=5,
        description="Route quality rating"
    )
    user_quality: Optional[float] = Field(
        None,
        ge=0,
        le=5,
        description="User's rating"
    )
    logbook_type: LogbookType = Field(..., description="Source of the tick data")
    difficulty_category: Optional[str] = Field(
        None,
        max_length=50,
        description="Difficulty category"
    )
    length_category: Optional[str] = Field(
        None,
        max_length=50,
        description="Length category"
    )
    season_category: Optional[str] = Field(
        None,
        max_length=50,
        description="Season category"
    )
    cur_max_rp_sport: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Current max sport redpoint"
    )
    cur_max_rp_trad: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Current max trad redpoint"
    )
    cur_max_boulder: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Current max boulder"
    )
    performance_data: Optional[PerformanceData] = Field(
        None,
        description="Performance metrics"
    )




class TickResponse(TickCreate):
    """Schema for tick response with metadata."""
    id: int = Field(..., ge=1, description="Tick ID")
    user_id: UUID4 = Field(..., description="User ID")
    created_at: date = Field(..., description="Creation timestamp")
    discipline: Optional[ClimbingDiscipline] = Field(None, description="Climbing discipline")


class BatchTickCreate(BaseModel):
    """Schema for batch tick creation."""
    ticks: List[TickCreate] = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="List of ticks to create"
    )

class RefreshStatus(BaseModel):
    """Schema for data refresh operation status."""
    status: str = Field(
        ...,
        pattern="^(pending|in_progress|completed|failed)$",
        description="Status of the refresh operation"
    )
    message: str = Field(
        ...,
        max_length=500,
        description="Status message"
    )
    last_sync: Optional[date] = Field(None, description="Last successful sync date")
    items_processed: Optional[int] = Field(
        None,
        ge=0,
        description="Number of items processed"
    )

class Tag(BaseModel):
    """Schema for tick categorization tags."""
    name: str = Field(
        ...,
        min_length=1,
        max_length=50,
        pattern="^[a-zA-Z0-9-_ ]+$",
        description="Tag name"
    )


class TagCreate(Tag):
    """Schema for creating a new tag."""
    pass

class TagResponse(Tag):
    """Schema for tag response with metadata."""
    id: int = Field(..., ge=1, description="Tag ID")


class UserTicksWithTags(TickResponse):
    """Schema for tick data with associated tags and performance data."""
    tags: List[TagResponse] = Field(
        default_factory=list,
        max_length=20,
        description="Associated tags"
    )
    performance_pyramid: Optional[Dict[str, Any]] = Field(
        None,
        description="Associated pyramid data"
    )


class BulkTagUpdate(BaseModel):
    """Schema for bulk tag operations."""
    tick_ids: List[int] = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="List of tick IDs to update"
    )
    tags: List[str] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Tags to apply"
    )
    operation: str = Field(
        ...,
        pattern="^(add|remove|set)$",
        description="Operation to perform (add/remove/set)"
    )

class GradeConversion(BaseModel):
    """Schema for grade conversion requests."""
    grade: str = Field(
        ...,
        max_length=50,
        description="Grade to convert"
    )
    source_scale: str = Field(
        ...,
        max_length=20,
        description="Source grading scale"
    )
    target_scale: str = Field(
        ...,
        max_length=20,
        description="Target grading scale"
    )

class GradeConversionResponse(BaseModel):
    """Schema for grade conversion results."""
    original_grade: str = Field(
        ...,
        max_length=50,
        description="Original grade"
    )
    converted_grade: str = Field(
        ...,
        max_length=50,
        description="Converted grade"
    )
    binned_code: int = Field(
        ...,
        ge=0,
        le=300,
        description="Numeric grade code"
    )
    equivalent_grades: Dict[str, str] = Field(
        ...,
        description="Grade in other scales"
    )

class DataImportStatus(BaseModel):
    """Schema for data import job status."""
    import_id: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Import job identifier"
    )
    status: str = Field(
        ...,
        pattern="^(pending|in_progress|completed|failed)$",
        description="Current status"
    )
    total_items: int = Field(
        ...,
        ge=0,
        description="Total items to import"
    )
    processed_items: int = Field(
        ...,
        ge=0,
        description="Items processed"
    )
    errors: List[Dict[str, Any]] = Field(
        default_factory=list,
        max_length=1000,
        description="Import errors"
    )
    warnings: List[Dict[str, Any]] = Field(
        default_factory=list,
        max_length=1000,
        description="Import warnings"
    )
    created_at: date = Field(..., description="Import start time")
    completed_at: Optional[date] = Field(None, description="Import completion time")


    @model_validator(mode="after")
    def validate_import_status(self) -> "DataImportStatus":
        """Validate import status data."""
        if self.processed_items > self.total_items:
            raise ValueError("Processed items cannot exceed total items")
        if (self.completed_at and self.created_at and 
            self.completed_at < self.created_at):
            raise ValueError("Completion time cannot be before creation time")
        return self 



class PerformanceDataUpdate(BaseModel):
    """Schema for performance data in batch updates."""
    first_sent: Optional[date] = Field(None, description="Date of first successful send")
    crux_angle: Optional[CruxAngle] = Field(None, description="Angle of the crux")
    crux_energy: Optional[CruxEnergyType] = Field(None, description="Energy type of the crux")
    num_attempts: Optional[int] = Field(None, ge=1, le=1000, description="Number of attempts")
    days_attempts: Optional[int] = Field(None, ge=1, le=365, description="Days spent attempting")
    num_sends: Optional[int] = Field(None, ge=0, le=1000, description="Number of successful sends")
    description: Optional[str] = Field(None, max_length=1000, description="Additional notes")
    agg_notes: Optional[str] = Field(None, max_length=1000, description="Aggregated notes")

class LogbookTickUpdate(TickCreate):
    """Schema for creating or updating ticks in batch operations."""
    id: Optional[int] = Field(None, ge=1, description="Tick ID for updates")
    performance_data: Optional[PerformanceDataUpdate] = Field(None, description="Performance metrics")
    tags: Optional[List[str]] = Field(None, max_length=20, description="Tags for the tick")

class LogbookBatchUpdate(BaseModel):
    """Schema for batch tick operations."""
    creates: List[LogbookTickUpdate] = Field(default_factory=list, description="Ticks to create")
    updates: List[LogbookTickUpdate] = Field(default_factory=list, description="Ticks to update")
    deletes: List[int] = Field(default_factory=list, description="Tick IDs to delete")

class LogbookBatchUpdateResponse(BaseModel):
    """Schema for batch update response."""
    success: bool = Field(..., description="Operation success status")
    created: List[int] = Field(..., description="IDs of created ticks")
    updated: List[int] = Field(..., description="IDs of updated ticks")
    deleted: List[int] = Field(..., description="IDs of deleted ticks")
    errors: Optional[Dict[str, Dict[int, str]]] = Field(
        None,
        description="Errors indexed by operation type and item index"
    )